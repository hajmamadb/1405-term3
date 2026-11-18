$(document).ready(function () {
  // in phone
  if (window.innerWidth < 992) {
    var spans = document.querySelectorAll('.circle-container-phone span');
    var numItems = 12;
    var containerSize = 480;
    var spanSize = 50;
    let radius = 180;
    let currentAngle = 45;
    let marginTop = 40;
    let marginLeft = -5;
    let activeIndex = 6;
    titleContent = '.menu-title';
    function positionSpans() {
      $('.circle-container-phone span').each(function (index) {
        const angle = currentAngle + index * (360 / numItems);
        const x = radius * Math.cos(angle * Math.PI / 180) + marginLeft;
        const y = radius * Math.sin(angle * Math.PI / 180) + marginTop;
        const xInt = parseInt(x)
        $(this).css({
          transform: `translate(${x}px, ${y}px)`
        });
        
        change_back(xInt, this)
      });

    }

    positionSpans();

    window.updateMargins = function () {
      marginTop = parseInt(document.getElementById('margin-top').value) || 0;
      marginLeft = parseInt(document.getElementById('margin-left').value) || 0;
      radius = parseInt(document.getElementById('radius').value) || 200;
      positionSpans();
    };

    window.toRoute = function () {
      spans[activeIndex].classList.remove('active');

      activeIndex = (activeIndex - 1 + numItems) % numItems;

      spans[activeIndex].classList.add('active');
      title = $(spans[activeIndex]).data("title");
      $(titleContent).text(title);

      $('.content-slider-active').removeClass('content-slider-active').addClass('content-slider-deactive');
      content = '#' + $(spans[activeIndex]).data("content");
      $(content).addClass('content-slider-active');
      $(content).removeClass('content-slider-deactive');

      currentAngle += 30;
      positionSpans();

    };

    $('#radius').on('input', function () {
      radius = parseInt($(this).val());
      positionSpans();
    });

    function startInterval() {
      intervalId = setInterval(function () { return toRoute() }, 5500);
    }

    startInterval()

    $('.circle-container-phone span').on('click', function () {
      clearInterval(intervalId);
      clickIndex = $(this).index();

      if (activeIndex == clickIndex) { return }
      if (activeIndex > clickIndex) { i = activeIndex - clickIndex; }
      if (activeIndex < clickIndex) { i = activeIndex + (numItems - clickIndex); }
      for (j = 0; j < i; j++) {
        toRoute();
      }

      startInterval()
    });
    items = ['item-menu-phone-1', 'item-menu-phone-2', 'item-menu-phone-3', 'item-menu-phone-4', 'item-menu-phone-5'];

  }
  // in desktop
  else {
    var spans = document.querySelectorAll('.circle-container span');
    var numItems = 12;
    var containerSize = 480;
    var spanSize = 50;
    let radius = 180;
    let currentAngle = 45;
    let marginTop = -8;
    let marginLeft = -5;
    let activeIndex = 6;
    titleContent = '#menu-title-desktop';
    function positionSpans() {
      $('.circle-container span').each(function (index) {
        const angle = currentAngle + index * (360 / numItems);
        let x = radius * Math.cos(angle * Math.PI / 180) + marginLeft;
        let y = radius * Math.sin(angle * Math.PI / 180) + marginTop;
        const xInt = parseInt(x)

        if ((xInt > 90 && xInt < 130) || (xInt < -90 && xInt > -130)) {
          y = y + 10
        }
        else if ((xInt > -177 && xInt < -110 && y > -149) || (xInt > 110 && xInt < 177)) {
          y = y - 20
        }

        $(this).css({
          transform: `translate(${x}px, ${y}px)`
        });

        change_back(xInt, this)
      });
    }

    positionSpans();

    window.updateMargins = function () {
      marginTop = parseInt(document.getElementById('margin-top').value) || 0;
      marginLeft = parseInt(document.getElementById('margin-left').value) || 0;
      radius = parseInt(document.getElementById('radius').value) || 200;
      positionSpans();
    };

    window.toRoute = function () {
      spans[activeIndex].classList.remove('active');

      activeIndex = (activeIndex - 1 + numItems) % numItems;

      spans[activeIndex].classList.add('active');
      title = $(spans[activeIndex]).data("title");
      $(titleContent).text(title);

      $('.content-slider-active').removeClass('content-slider-active').addClass('content-slider-deactive');
      content = '#' + $(spans[activeIndex]).data("content");
      $(content).addClass('content-slider-active');
      $(content).removeClass('content-slider-deactive');

      currentAngle += 30;
      positionSpans();

    };

    $('#radius').on('input', function () {
      radius = parseInt($(this).val());
      positionSpans();
    });

    function startInterval() {
      intervalId = setInterval(function () { return toRoute() }, 15500);
    }

    startInterval()

    $('.circle-container span').on('click', function () {
      clearInterval(intervalId);
      clickIndex = $(this).index();

      if (activeIndex == clickIndex) { return }
      if (activeIndex > clickIndex) { i = activeIndex - clickIndex; }
      if (activeIndex < clickIndex) { i = activeIndex + (numItems - clickIndex); }
      for (j = 0; j < i; j++) {
        toRoute();
      }

      startInterval()
    });
  }


});

const change_back = (x, elem) => {
  if (x > 0) {
    $(elem).css('background', 'radial-gradient(farthest-side at 100% 0%,rgba(224, 224, 224, 0.918) 100% ,#fcfcfc 120%)')
  }

  if (x < 0) {
    $(elem).css('background', 'radial-gradient(farthest-side at 0% 0%,rgba(224, 224, 224, 0.918) 100% ,#fcfcfc 120%)')
  }
}

$(window).on('resize', function () {
  location.reload();
});